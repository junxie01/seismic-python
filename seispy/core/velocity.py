# coding=utf-8
"""
This module facilitates access to velocity model data.

.. todo::
   Make a ScalarField class to abstract behaviour in this class.

.. autoclass:: VelocityModel
   :special-members:
   :private-members:
   :members:
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import constants as _constants
from . import coords as _coords
from . import geometry as _geometry
from . import mapping as _mapping


class VelocityModel(object):
    """
    A callable class providing a queryable container for seismic
    velocities in a 3D volume.

    :param str inf: path to input file containing phase velocity
                    data
    :param str fmt: format of input file
    """
    def __init__(self, inf=None, fmt=None, topo=None, **kwargs):
        if inf is None:
            return
        if topo is None:
            self.topo = lambda _, __: _constants.EARTH_RADIUS
        else:
            self.topo = topo

        if fmt.upper() == "FANG":
            self._read_fang(inf, **kwargs)
        elif fmt.upper() in ("FM3D", "FMM3D"):
            raise(NotImplementedError(f"Unrecognized format - {fmt}"))
            self._read_fmm3d(inf, **kwargs)
        elif fmt.upper() in ("ABZ", "ABZ2015", "ABZ15"):
            self._read_abz(inf, **kwargs)
        elif fmt.upper() in ("UCVM", "SCEC-UCVM"):
            self._read_ucvm(inf, **kwargs)
        elif fmt.upper() == "NPZ":
            self._read_npz(inf)
        else:
            raise(ValueError(f"Unrecognized format - {fmt}"))

    def from_DataFrame(self, df):
        """
        Initialize VelocityModel from a pandas.DataFrame. Input
        DataFrame must have *lat*, *lon*, *depth*, *Vp*, and *Vs*,
        fields.

        :param pandas.DataFrame df: DataFrame with velocity data
        """
        df["R"] = df["T"] = df["P"] = np.nan
        spher = _coords.as_geographic(df[["lat", "lon", "depth"]]
                                           ).to_spherical()
        df.loc[:, ["R", "T", "P"]] = spher
        df = df.sort_values(["R", "T", "P"])
        nR = len(df.drop_duplicates("R"))
        nT = len(df.drop_duplicates("T"))
        nP = len(df.drop_duplicates("P"))
        nodes = df[["R", "T", "P"]].values.reshape(nR, nT, nP, 3)
        self._nodes = _coords.as_spherical(nodes)
        Vp = df["Vp"].values.reshape(nR, nT, nP)
        Vs = df["Vs"].values.reshape(nR, nT, nP)
        self._Vp = Vp
        self._Vs = Vs
        return(self)

    def to_DataFrame(self):
        df = pd.DataFrame().from_dict({"R": self._nodes[...,0].flatten(),
                                       "T": self._nodes[...,1].flatten(),
                                       "P": self._nodes[...,2].flatten(),
                                       "Vp": self._Vp.flatten(),
                                       "Vs": self._Vs.flatten()})
        df["lat"] = df["lon"] = df["depth"] = np.nan
        geo = _coords.as_spherical(df[["R", "T", "P"]]).to_geographic()
        df.loc[:, ["lat", "lon", "depth"]] = geo
        df = df.sort_values(["lat", "lon", "depth"]).reset_index()
        return(df[["lat", "lon", "depth", "Vp", "Vs", "R", "T", "P"]])

    def __call__(self, phase, coords):
        """
        Return **phase**-velocity at given coordinates. A NULL value
        (-1) is returned for points above the surface.

        :param str phase: phase
        :param array-like coords: coordinates
        :returns: **phase**-velocity at coordinates
        :rtype: array-like
        """
        # Convert geographic coordinates to spherical
        rtp = _coords.as_geographic(coords).to_spherical()
        def func(coords):
            v = self._get_V(phase, *coords)
            return (self._get_V(phase, *coords))
        vv = np.array(list(map(func, rtp.reshape(-1, 3)))).reshape(rtp.shape[:-1])
        return(vv)

    def save(self, outf):
        np.savez(outf, nodes=self._nodes, Vp=self._Vp, Vs=self._Vs)

    def _read_npz(self, inf):
        inf = np.load(inf)
        self._nodes = _coords.as_spherical(inf["nodes"])
        self._Vp = inf["Vp"]
        self._Vs = inf["Vs"]

    def _read_ucvm(self, inf, Vp_key="cmb_vp", Vs_key="cmb_vs"):
        names=["lon", "lat", "Z", "surf", "vs30", "crustal", "cr_vp", "cr_vs",
               "cr_rho", "gtl", "gtl_vp", "gtl_vs", "gtl_rho", "cmb_algo",
               "cmb_vp", "cmb_vs", "cmb_rho"]
        df = pd.read_table(inf,
                      delim_whitespace=True,
                      header=None,
                      names=names)
        df["depth"] = df["Z"]*1e-3
        df["Vp"] = df[Vp_key]*1e-3
        df["Vs"] = df[Vs_key]*1e-3
        df["R"] = df["T"] = df["P"] = np.nan
        spher = _coords.as_geographic(df[["lat", "lon", "depth"]]
                                           ).to_spherical()
        df.loc[:, ["R", "T", "P"]] = spher
        df = df.sort_values(["R", "T", "P"])
        nR = len(df.drop_duplicates("R"))
        nT = len(df.drop_duplicates("T"))
        nP = len(df.drop_duplicates("P"))
        nodes = df[["R", "T", "P"]].values.reshape(nR, nT, nP, 3)
        self._nodes = _coords.as_spherical(nodes)
        Vp = df["Vp"].values.reshape(nR, nT, nP)
        Vs = df["Vs"].values.reshape(nR, nT, nP)
        self._Vp = Vp
        self._Vs = Vs
    
    def _read_abz(inf, **kwargs):
        raise(NotImplementedError("_read_abz not implemented"))

    def _read_fang(self, inf):
        with open(inf) as inf:
            lon = np.array([float(v) for v in inf.readline().split()])
            lat = np.array([float(v) for v in inf.readline().split()])
            depth = np.array([float(v) for v in inf.readline().split()])
            LAT, LON, DEPTH = np.meshgrid(lat, lon, depth, indexing="ij")
            VVp = np.zeros(LAT.shape)
            VVs = np.zeros(LAT.shape)
            for idepth in range(len(depth)):
                for ilat in range(len(lat)):
                    VVp[ilat, :, idepth] = np.array([float(v) for v in inf.readline().split()])
            for idepth in range(len(depth)):
                for ilat in range(len(lat)):
                    VVs[ilat, :, idepth] = np.array([float(v) for v in inf.readline().split()])
        spher = _coords.as_geographic(np.stack([LAT.flatten(),
                                                      LON.flatten(),
                                                      DEPTH.flatten()],
                                                     axis=1)
                                           ).to_spherical()
        df = pd.DataFrame.from_dict({"R": spher[:, 0],
                                     "T": spher[:, 1],
                                     "P": spher[:, 2],
                                     "Vp": VVp.flatten(),
                                     "Vs": VVs.flatten()})
        df = df.sort_values(["R", "T", "P"])
        nR = len(df.drop_duplicates("R"))
        nT = len(df.drop_duplicates("T"))
        nP = len(df.drop_duplicates("P"))
        self._nodes = df[["R", "T", "P"]].values.reshape(nR, nT, nP, 3)
        Vp = df["Vp"].values.reshape(nR, nT, nP)
        Vs = df["Vs"].values.reshape(nR, nT, nP)
        self._Vp = Vp
        self._Vs = Vs

    def _get_V(self, phase: str, rho: float, theta: float, phi: float)->float:
        phase = _verify_phase(phase)
        if phase == "P":
            VV = self._Vp
        elif phase == "S":
            VV = self._Vs
        else:
            raise(ValueError(f"Unrecognized phase type: {phase}"))


        idx = np.nonzero(self._nodes[:, 0, 0, 0] == rho)[0]
        if idx.size > 0:
            iR0, iR1 = idx[0], idx[0]
        else:
            idxl = np.nonzero(self._nodes[:, 0, 0, 0] < rho)[0]
            idxr = np.nonzero(self._nodes[:, 0, 0, 0] > rho)[0]
            if not np.any(idxl):
                iR0, iR1 = 0, 0
            elif not np.any(idxr):
                iR0, iR1 = -1, -1
            else:
                iR0, iR1 = idxl[-1], idxr[0]
        if iR0 == iR1:
            dR, drho = 1, 0
        else:
            dR = self._nodes[iR1, 0, 0, 0]-self._nodes[iR0, 0, 0, 0]
            drho = (rho - self._nodes[iR0, 0, 0, 0])


        idx = np.nonzero(self._nodes[0, :, 0, 1] == theta)[0]
        if idx.size > 0:
            iT0, iT1 = idx[0], idx[0]
        else:
            idxl = np.nonzero(self._nodes[0, :, 0, 1] < theta)[0]
            idxr = np.nonzero(self._nodes[0, :, 0, 1] > theta)[0]
            if not np.any(idxl):
                iT0, iT1 = 0, 0
            elif not np.any(idxr):
                iT0, iT1 = -1, -1
            else:
                iT0, iT1 = idxl[-1], idxr[0]
        if iT0 == iT1:
            dT, dtheta = 1, 0
        else:
            dT = self._nodes[0, iT1, 0, 1]-self._nodes[0, iT0, 0, 1]
            dtheta = (theta - self._nodes[0, iT0, 0, 1])


        idx = np.nonzero(self._nodes[0, 0, :, 2] == phi)[0]
        if idx.size > 0:
            iP0, iP1 = idx[0], idx[0]
        else:
            idxl = np.nonzero(self._nodes[0,0,:,2] < phi)[0]
            idxr = np.nonzero(self._nodes[0,0,:,2] > phi)[0]
            if not np.any(idxl):
                iP0, iP1 = 0, 0
            elif not np.any(idxr):
                iP0, iP1 = -1, -1
            else:
                iP0, iP1 = idxl[-1], idxr[0]
        if iP0 == iP1:
            dP, dphi = 1, 0
        else:
            dP = self._nodes[0,0,iP1,2]-self._nodes[0,0,iP0,2]
            dphi = (phi - self._nodes[0,0,iP0,2])


        V000 = VV[iR0,iT0,iP0]
        V001 = VV[iR0,iT0,iP1]
        V010 = VV[iR0,iT1,iP0]
        V011 = VV[iR0,iT1,iP1]
        V100 = VV[iR1,iT0,iP0]
        V101 = VV[iR1,iT0,iP1]
        V110 = VV[iR1,iT1,iP0]
        V111 = VV[iR1,iT1,iP1]

        V00 = V000 + (V100 - V000)*drho/dR
        V01 = V001 + (V101 - V001)*drho/dR
        V10 = V010 + (V110 - V010)*drho/dR
        V11 = V011 + (V111 - V011)*drho/dR

        V0 = V00 + (V10 - V00)*dtheta/dT
        V1 = V01 + (V11 - V01)*dtheta/dT

        V = V0 + (V1 - V0)*dphi/dP

        return (V)

    def regrid(self, R, T, P):
        Vp = np.empty(shape=R.shape)
        Vs = np.empty(shape=R.shape)
        for store, phase, index in ((Vp, "Vp", 0), (Vs, "Vs", 1)):
            for (ir, it, ip) in [(ir, it, ip) for ir in range(R.shape[0])
                                              for it in range(T.shape[1])
                                              for ip in range(P.shape[2])]:
                r, theta, phi = R[ir, it, ip], T[ir, it, ip], P[ir, it, ip]
                store[ir, it, ip] = self._get_V(r, theta, phi, phase)
        self.values["Vp"] = Vp
        self.values["Vs"] = Vs
        self.nodes["r"], self.nodes["theta"], self.nodes["phi"] = R, T, P
        self.nodes["nr"] = R.shape[0]
        self.nodes["ntheta"] = T.shape[1]
        self.nodes["nphi"] = P.shape[2]
        self.nodes["dr"] = (R[:,0,0][-1] - R[:,0,0][0]) / (R.shape[0] - 1)
        self.nodes["dtheta"] = (T[0,:,0][-1] - T[0,:,0][0]) / (T.shape[1] - 1)
        self.nodes["dphi"] = (P[0,0,:][-1] - P[0,0,:][0]) / (P.shape[2] - 1)
        self.nodes["r_min"], self.nodes["r_max"] = np.min(R), np.max(R)
        self.nodes["theta_min"], self.nodes["theta_max"] = np.min(T), np.max(T)
        self.nodes["phi_min"], self.nodes["phi_max"] = np.min(P), np.max(P)

    def regularize(self, nr, ntheta, nphi):
        R, T, P = np.meshgrid(np.linspace(self.nodes["r_min"],
                                          self.nodes["r_max"],
                                          nr),
                              np.linspace(self.nodes["theta_min"],
                                          self.nodes["theta_max"],
                                          ntheta),
                              np.linspace(self.nodes["phi_min"],
                                          self.nodes["phi_max"],
                                          nphi),
                              indexing="ij")
        self.regrid(R, T, P)

    def extract_slice(self, phase="P", origin=(33.5, -116.5, 0), strike=0,
                      length=50, zmin=0, zmax=25, nx=25, nz=25):
        r"""
        Extract an arbitrarily oriented vertical slice from the VelocityModel.
        """
        n = np.linspace(-length, length, nx)
        d = np.linspace(zmin, zmax, nz)
        nn, dd = np.meshgrid(n, d)
        ee = np.zeros(nn.shape)
        ned = _coords.as_ned(np.stack([nn, ee, dd], axis=2))
        ned.set_origin(origin)
        geo = ned.to_geographic()
        vv = self(phase, geo)
        # vv = self("Vp", geo)/self("Vs", geo)
        return (vv, ned, geo)

    def plot(self, phase="P", ix=None, iy=None, iz=None, type="fancy",
             events=None, faults=False, vmin=None, vmax=None,
             basemap_kwargs=None):
        r"""
        This needs to be cleaned up, but it will plot a velocity model
        (map-view) and two perendicular, user-selected vertical slices.
        """
        phase = _verify_phase(phase)
        if phase == "P":
            data = self._Vp
        elif phase == "S":
            data = self._Vs
        ix = int((self._nodes.shape[2]-1)/2) if ix is None else ix
        iy = int((self._nodes.shape[1]-1)/2) if iy is None else iy
        iz = -1 if iz is None else iz
        vmin = data.min() if vmin is None else vmin
        vmax = data.max() if vmax is None else vmax
        basemap_kwargs = {} if basemap_kwargs is None else basemap_kwargs
        origin = self._nodes.to_geographic()[iz, iy, ix]
        if events is not None:
            events = seispy.coords.as_geographic(events[["lat", "lon", "depth"]])
        fig = plt.figure(figsize=(11,8.5))
        ax0 = fig.add_axes((0.05, 0.3, 0.7, 0.65))
        nodes = self._nodes.to_geographic()
        _basemap_kwargs = dict(llcrnrlat=nodes[..., 0].min(),
                               llcrnrlon=nodes[..., 1].min(),
                               urcrnrlat=nodes[..., 0].max(),
                               urcrnrlon=nodes[..., 1].max())
        basemap_kwargs = {**_basemap_kwargs, **basemap_kwargs}
        bm = _mapping.Basemap(basekwargs=basemap_kwargs,
                              ax=ax0,
                              meridian_labels=[False, False, True, False])
        qmesh = bm.overlay_pcolormesh(nodes[iz, ..., 1].flatten(),
                                      nodes[iz, ..., 0].flatten(),
                                      data[iz].flatten(),
                                      cmap=plt.get_cmap("jet_r"),
                                      vmin=vmin,
                                      vmax=vmax)
        if faults is True:
            bm.add_faults()
        if events is not None:
            bm.scatter(events[:,1], events[:,0], 
                       c="k",
                       s=0.1,
                       linewidths=0, 
                       zorder=3,
                       alpha=0.25)
        (xmin, ymin), (xmax, ymax) = bm.ax.get_position().get_points()
        cax = fig.add_axes((0.9, ymin, 0.025, ymax - ymin))
        cbar = fig.colorbar(qmesh, cax=cax)
        cbar.ax.invert_yaxis()
        cbar.set_label(f"$V_{phase.lower()}$ "+r"[$\frac{km}{s}$]")
        # Plot the NS vertical slice
        bm.axvline(x=origin[1], zorder=3, linestyle="--", color="k")
        ax_right = fig.add_axes((xmax, ymin, 1-xmax, ymax-ymin))
        ned = self._nodes[:, :, ix].to_ned(origin=origin)
        ax_right.pcolormesh(ned[..., 2], ned[..., 0], data[:, :, ix],
                            cmap=plt.get_cmap("jet_r"),
                            vmin=vmin,
                            vmax=vmax)
        
        ax_right.set_aspect(1)
        ax_right.yaxis.tick_right()
        ax_right.yaxis.set_label_position("right")
        ax_right.set_xlabel("[$km$]", rotation=180)
        ax_right.set_ylabel("[$km$]")
        ax_right.tick_params(axis="y", labelrotation=90)
        ax_right.tick_params(axis="x", labelrotation=90)
        # Plot the EW vertical slice
        bm.axhline(y=origin[0], zorder=3, linestyle="--", color="k")
        ax_bottom = fig.add_axes((xmin, 0, xmax-xmin, ymin))
        ned = self._nodes[:, iy, :].to_ned(origin=origin)
        ax_bottom.pcolormesh(ned[..., 1], ned[..., 2], data[:, iy, :],
                             cmap=plt.get_cmap("jet_r"),
                             vmin=vmin,
                             vmax=vmax)
        ax_bottom.invert_yaxis()
        ax_bottom.set_aspect(1)
        ax_bottom.set_xlabel("[$km$]")
        ax_bottom.set_ylabel("[$km$]")
        def post_processing(bm, ax_right, ax_bottom, wpad=0.05, hpad=0.05):
            (xmin, ymin), (xmax, ymax) = bm.ax.get_position().get_points()
            (xmin0, ymin0), (xmax0, ymax0) = bm.ax.get_position().get_points()
            (xmin_r, ymin_r), (xmax_r, ymax_r) = ax_right.get_position().get_points()
            (xmin_b, ymin_b), (xmax_b, ymax_b) = ax_bottom.get_position().get_points()
            dx0, dy0 = (xmax0-xmin0), (ymax0-ymin0)
            dx_r, dy_r = (xmax_r-xmin_r), (ymax_r-ymin_r)
            dx_b, dy_b = (xmax_b-xmin_b), (ymax_b-ymin_b)
            aspect_r = dy_r / dx_r
            aspect_b = dy_b / dx_b
            ax_right.set_position((xmax0+wpad, ymin0, 0.1, dy0))
            ax_bottom.set_position((xmin0, ymin0-dx0*aspect_b-hpad, dx0, dx0*aspect_b))
        return ((bm, ax_right, ax_bottom), post_processing)

    def plot_slice(self, phase="P", origin=(33.5, -116.5, 0), strike=0,
                   length=50, zmin=0, zmax=25, nx=25, nz=25, ax=None):
        r"""
        Plot an arbitrarily oriented vertical slice from the VelocityModel.
        """
        vv, ned, geo = self.extract_slice(phase=phase,
                                          origin=origin,
                                          strike=strike,
                                          length=length,
                                          zmin=zmin,
                                          zmax=zmax,
                                          nx=nx,
                                          nz=nz)
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(1, 1, 1, aspect=1)
        xx, yy = ned[..., 0], ned[..., 2]
        qmesh = ax.pcolormesh(xx, yy, vv, cmap=plt.get_cmap("jet_r"))
        ax.invert_yaxis()
        return(ax, qmesh)

def _verify_phase(phase: str)->str:
    if phase.upper() == "P" or  phase.upper() == "VP":
        phase = "P"
    elif phase.upper() == "S" or phase.upper() == "VS":
        phase = "S"
    else:
        raise(ValueError("invalid phase type - {}".format(phase)))
    return(phase)

def test():
    #vm = VelocityModel("/Users/malcolcw/Projects/Wavefront/examples/example2/vgrids.in", "fmm3d")
    #grid = vm.v_type_grids[1][1]["grid"]
    #print(vm(1, 3, 0.5, 0.5, 0))
    #vm.v_type_grids[1][1]
    #print(v("Vp", 33.0, -116.9, 3.0))
    vm = VelocityModel("/Users/malcolcw/Projects/Shared/Velocity/FANG2016/original/VpVs.dat", "fang")
    with open("/Users/malcolcw/Projects/Wavefront/pywrap/example5/vgrids.in", "w") as outf:
        outf.write(str(vm))
if __name__ == "__main__":
    test()
    print("velocity.py is not an executable script.")
    exit()
