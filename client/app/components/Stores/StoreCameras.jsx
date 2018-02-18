import React from 'react';
import {Col, Row, Panel} from 'react-bootstrap';
import {withRouter, Link} from "react-router-dom";
import {branch} from "recompose";
import ReactTable from 'react-table'
import _ from 'underscore';
import axios from "axios/index";
import {Stomp} from 'stompjs/lib/stomp.min';

class StoreCameras extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            selectedCamera: this.props.match.params.cameraId,
            cameraImageCacheBuster: Date.now()
        };

        this.camera = _.findWhere(this.props.store.cameras, {id: this.state.selectedCamera});

        if (this.camera) {
            var headers = {durable: false, "auto-delete": false, exclusive: false};
            this.cameraSubscription = this.props.messagingClient.subscribe("/exchange/" + this.camera.id, (message) =>
            {
                const body = JSON.parse(message.body);
                if (body.type === 'image-updated')
                {
                    this.reloadCameraImage();
                }
            }, headers);
        }
    }

    reloadCameraImage()
    {
        // Reload the camera image by changing the cache-buster query
        this.setState({cameraImageCacheBuster: Date.now()});
    }


    componentDidMount()
    {
        if (this.camera)
        {
            axios({
                method: 'post',
                url: `/store/${this.props.store._id}/cameras/${this.camera.id}/record`
            })
        }
    }

    componentWillUnmount()
    {
        if (this.cameraSubscription)
        {
            this.cameraSubscription.unsubscribe();
        }

    }

    render() {
        return (
            <div>
                <br/>
                <Row>
                    <Col md={3}>
                        <div className="panel b">
                            <div className="panel-body">
                                <strong className="text-muted">Cameras</strong>
                            </div>
                            <div className="list-group">
                                {
                                    this.props.store.cameras &&
                                    this.props.store.cameras.map((camera) =>
                                        <Link key={camera.id} to={"/store/" + this.props.store._id + "/camera/" + camera.id}
                                           className={"list-group-item " + (camera.id === this.state.selectedCamera ? " active" : "")}>
                                            <span>{camera.id}</span>
                                        </Link>
                                    )
                                }
                            </div>
                        </div>
                    </Col>
                    {this.camera &&
                    <Col md={9}>
                        <div className="panel b">
                            <div className="panel-heading">
                                <div className="pull-right">
                                    <div className="label label-success">operating normally</div>
                                </div>
                                <h4 className="m0">{this.camera.id}</h4>
                            </div>
                            <table className="table">
                                <tbody>
                                <tr>
                                    <td>
                                        <strong>Location</strong>
                                    </td>
                                    <td>Unsure</td>
                                </tr>
                                <tr>
                                    <td>
                                        <strong>Model</strong>
                                    </td>
                                    <td>
                                        Logitech C170
                                    </td>
                                </tr>
                                <tr>
                                    <td>
                                        <strong>Status</strong>
                                    </td>
                                    <td>
                                        Normal
                                    </td>
                                </tr>
                                </tbody>
                            </table>
                        </div>
                        <div className="panel b">
                            <div className="panel-heading">
                                <h4 className="m0">Live Feed</h4>
                            </div>

                            <div className="panel-body">
                                <img src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/cameras/" + this.camera.id + "/image?" + this.state.cameraImageCacheBuster} />
                            </div>
                        </div>
                        <div className="panel b">
                            <div className="panel-heading">
                                <h4 className="m0">Location</h4>
                            </div>

                            <div className="panel-body">
                                <img src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/store_layout?" + Date.now()} />
                            </div>

                            <div className="panel-footer text-center">
                                <button type="button" className="btn btn-default">Recalibrate</button>
                            </div>
                        </div>
                    </Col>
                    }
                </Row>
            </div>
        );
    }
}

export default withRouter(StoreCameras);


